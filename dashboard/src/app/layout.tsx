import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Connected Warner · Tableau de bord",
  description: "Suivi des boîtiers d’aide Connected Warner — aperçu de démonstration.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="fr"><body>{children}</body></html>;
}
