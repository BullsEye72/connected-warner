import asyncio
import json
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import dashboard as d
from main import Boitier, ATTENTE, CONFIRMEE


def configuration(**options):
    values = dict(DASHBOARD_ACTIF=True, DASHBOARD_URL="https://connected-warner.vercel.app",
                  DASHBOARD_APPAREIL_ID="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", DASHBOARD_CLE="cw_" + "A" * 43)
    values.update(options)
    return SimpleNamespace(**values)


class ValidationTests(unittest.TestCase):
    def test_configuration_https_sans_fuite_de_secret(self):
        self.assertEqual(d.valider_configuration(configuration()), "connected-warner.vercel.app")
        for options in ({"DASHBOARD_URL": "http://example.com"}, {"DASHBOARD_URL": "https://example.com/path"},
                        {"DASHBOARD_URL": "https://user:password@example.com"}, {"DASHBOARD_CLE": "secret"},
                        {"DASHBOARD_APPAREIL_ID": "not-an-id"}):
            with self.assertRaises(ValueError) as error:
                d.valider_configuration(configuration(**options))
            self.assertNotIn("password", str(error.exception))
            self.assertNotIn("secret", str(error.exception))

    def test_charge_fermee_et_annulation_meme_apres_retour_repos(self):
        b = Boitier(journal=lambda _: None, ecart=lambda a, b: a - b)
        b.nouvelle_demande(0)
        b.annuler()
        r = d.instantane(b, "a" * 24, 1, 120, "1.29.0")
        self.assertEqual(r["state"], "annulee")
        self.assertEqual(r["request_id"], "a" * 24 + "-1")
        self.assertEqual(set(r), {"session", "sequence", "state", "uptime_seconds", "firmware_version", "micropython_version", "wifi_rssi", "request_id"})
        self.assertNotIn("JETON_PUSHBULLET", json.dumps(r))

    def test_dns_reponse_compressee_ttl_et_refus(self):
        question = b"\x07example\x03com\0\0\1\0\1"
        packet = b"AB" + struct.pack("!HHHHH", 0x8180, 1, 1, 0, 0) + question
        packet += b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, 4) + bytes([1, 2, 3, 4])
        self.assertEqual(d.lire_dns(packet, b"AB"), ("1.2.3.4", 60000))
        for broken in (packet[:20], packet[:-1], b"AB" + b"\x83\x80" + packet[4:], b"CD" + packet[2:]):
            with self.assertRaises(ValueError):
                d.lire_dns(broken, b"AB")

    def test_desactive_par_defaut_et_mauvaise_config_non_fatale(self):
        logs = []
        self.assertIsNone(d.creer_presence(SimpleNamespace(), None, None, logs.append))
        self.assertIsNone(d.creer_presence(configuration(DASHBOARD_CLE="bad"), None, None, logs.append))
        self.assertEqual(len(logs), 1)


class FakeSocket:
    def __init__(self, response):
        self.response = response
    def read(self, n):
        chunk, self.response = self.response[:n], self.response[n:]
        return chunk


class FakeTCP(FakeSocket):
    def __init__(self):
        super().__init__(b'HTTP/1.1 200 OK\r\nContent-Length: 17\r\n\r\n{"accepted":true}')
        self.sent, self.closed = b"", False
    def setblocking(self, value):
        assert value is False
    def connect(self, address):
        self.address = address
        raise OSError(115)
    def write(self, data):
        self.sent += bytes(data)
        return len(data)
    def close(self):
        self.closed = True


class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_transport_tls_sni_verifie_et_fermeture_socket(self):
        sock = FakeTCP()
        wraps = []
        def wrap(value, **options):
            wraps.append(options)
            return value
        transport = d.TransportHTTPS.__new__(d.TransportHTTPS)
        transport.c, transport.hote = configuration(), "connected-warner.vercel.app"
        transport.adresse, transport.date_dns, transport.ttl_ms, transport.pas_max_ms = "1.2.3.4", 0, 300000, 0
        transport.tls = SimpleNamespace(wrap_socket=wrap)
        poll = SimpleNamespace(register=lambda *a: None, unregister=lambda *a: None, poll=lambda *a: [(sock, 4)])
        sockets = SimpleNamespace(AF_INET=2, SOCK_STREAM=1, socket=lambda *a: sock)
        select = SimpleNamespace(poll=lambda: poll, POLLOUT=4, POLLERR=8, POLLHUP=16)
        with patch.dict("sys.modules", {"socket": sockets, "select": select}):
            status, _, body = await transport.envoyer({"test": True})
        self.assertEqual((status, body), (200, {"accepted": True}))
        self.assertTrue(sock.closed)
        self.assertEqual(wraps, [{"server_hostname": transport.hote, "do_handshake_on_connect": False}])
        self.assertIn(b"POST /api/devices/", sock.sent)
        self.assertIn(b"Authorization: Bearer cw_", sock.sent)
        self.assertNotIn(b"Pushbullet", sock.sent)

    async def test_annulation_connexion_ferme_le_socket_meme_avant_tls(self):
        sock = FakeTCP()
        transport = d.TransportHTTPS.__new__(d.TransportHTTPS)
        transport.adresse, transport.date_dns, transport.ttl_ms = "1.2.3.4", 0, 300000
        poll = SimpleNamespace(register=lambda *a: None, unregister=lambda *a: None, poll=lambda *a: [])
        sockets = SimpleNamespace(AF_INET=2, SOCK_STREAM=1, socket=lambda *a: sock)
        select = SimpleNamespace(poll=lambda: poll, POLLOUT=4, POLLERR=8, POLLHUP=16)
        with patch.dict("sys.modules", {"socket": sockets, "select": select}):
            task = asyncio.create_task(transport.envoyer({}))
            await asyncio.sleep(0.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(sock.closed)

    async def test_dns_annulable_sans_resolution_bloquante(self):
        sock = FakeTCP()
        sock.connect = lambda address: None
        sock.send = lambda data: None
        def pending(n):
            raise OSError(11)
        sock.recv = pending
        sockets = SimpleNamespace(AF_INET=2, SOCK_DGRAM=2, socket=lambda *a: sock)
        with patch.dict("sys.modules", {"socket": sockets}):
            task = asyncio.create_task(d.resoudre("example.com", "192.168.1.1"))
            await asyncio.sleep(0.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(sock.closed)

    async def test_http_corps_bufferise_longueur_blocs_et_fermeture(self):
        for response in (
            b'HTTP/1.1 200 OK\r\nContent-Length: 17\r\n\r\n{"accepted":true}',
            b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n11\r\n{"accepted":true}\r\n0\r\n\r\n',
            b'HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n{"accepted":true}',
        ):
            status, _, value = await d.lire_reponse_http(d.LecteurTLS(FakeSocket(response)))
            self.assertEqual(status, 200)
            self.assertEqual(value, {"accepted": True})

    def setUp(self):
        self.b = Boitier(journal=lambda _: None)
        self.b.reseau.horloge_prete = True
        self.logs = []
        self.sent = []
        self.clock = 0
        self.patch = patch.object(d, "maintenant_ms", side_effect=lambda: self.clock)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.transport = SimpleNamespace(wlan=SimpleNamespace(isconnected=lambda: True), pas_max_ms=0)
        async def send(report):
            self.sent.append(report)
            return 200, {}, {"accepted": True}
        self.transport.envoyer = send
        self.p = d.PresenceDashboard(configuration(), self.b, SimpleNamespace(temps=lambda: self.clock // 1000), self.transport, self.logs.append)

    async def tick(self, ms, aide=False):
        self.clock = ms
        self.p.actualiser(ms, aide)
        for _ in range(5):
            await asyncio.sleep(0)

    async def test_demarrage_evenement_et_dix_minutes(self):
        await self.tick(1999)
        self.assertEqual(self.sent, [])
        await self.tick(2000)
        self.assertEqual(len(self.sent), 1)
        await self.tick(601999)
        self.assertEqual(len(self.sent), 1)
        await self.tick(602000)
        self.assertEqual(len(self.sent), 2)
        self.b.changer_etat(CONFIRMEE)
        await self.tick(602001)
        self.assertEqual(self.sent[-1]["state"], "confirmee")
        self.assertGreater(self.sent[-1]["sequence"], self.sent[-2]["sequence"])

    async def test_panne_site_backoff_aucun_changement_du_boitier(self):
        async def fail(report):
            self.sent.append(report)
            raise OSError("secret-never-logged")
        self.transport.envoyer = fail
        await self.tick(2000)
        await self.tick(16000)
        self.assertEqual(len(self.sent), 1)
        await self.tick(17000)
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self.b.etat, "REPOS")
        self.assertNotIn("secret-never-logged", "".join(self.logs))

    async def test_refus_cle_suspend_jusqu_au_redemarrage(self):
        async def refuse(report):
            self.sent.append(report)
            return 401, {}, {}
        self.transport.envoyer = refuse
        await self.tick(2000)
        await self.tick(700000)
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(self.p.suspendu)

    async def test_appui_annule_et_libere_le_transport_sans_attendre(self):
        stopped = asyncio.Event()
        async def hanging(report):
            try:
                await asyncio.sleep(3600)
            finally:
                stopped.set()
        self.transport.envoyer = hanging
        await self.tick(2000)
        await self.tick(2005, aide=True)
        await asyncio.wait_for(stopped.wait(), 0.5)
        self.assertIsNone(self.p.envoye)
        self.assertEqual(self.b.etat, "REPOS")

    async def test_pushbullet_prioritaire_et_sans_faux_heartbeat(self):
        self.b.reseau.en_cours = {"nature": "AIDE"}
        await self.tick(2000)
        self.assertEqual(self.sent, [])
        self.b.reseau.en_cours = None
        await self.tick(3999)
        self.assertEqual(self.sent, [])
        await self.tick(4000)
        self.assertEqual(len(self.sent), 1)

    async def test_pas_horloge_ou_wifi_differe_sans_casser_alertes(self):
        self.b.reseau.horloge_prete = False
        await self.tick(2000)
        self.assertEqual(self.sent, [])
        self.b.reseau.horloge_prete = True
        self.transport.wlan.isconnected = lambda: False
        await self.tick(4000)
        self.assertEqual(self.sent, [])


if __name__ == "__main__":
    unittest.main()
