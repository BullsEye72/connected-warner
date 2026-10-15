import Link from "next/link";

export function Brand() {
  return <Link className="brand" href="/" aria-label="Connected Warner, accueil"><span className="brand-mark" aria-hidden="true">↗</span><span>connected<span className="brand-sub">warner</span></span></Link>;
}
