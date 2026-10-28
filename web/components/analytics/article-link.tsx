"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { useAnalytics } from "./provider";

export function ArticleLink({ href, risk, children, className, title, target, rel }: {
  href: string; risk?: string; children: ReactNode; className?: string; title?: string; target?: string; rel?: string;
}) {
  const { openArticle } = useAnalytics();
  return <Link href={href} className={className} title={title} target={target} rel={rel}
    onClick={() => openArticle(href, risk)}
    onAuxClick={(event) => { if (event.button === 1) openArticle(href, risk); }}>
    {children}
  </Link>;
}
