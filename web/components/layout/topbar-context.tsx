//© 2025 University of Aberdeen. All rights reserved


"use client";

import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useState } from "react";

type TopbarContextValue = {
  content: ReactNode | null;
  setContent: (node: ReactNode | null) => void;
  rightContent: ReactNode | null;
  setRightContent: (node: ReactNode | null) => void;
};

const TopbarContext = createContext<TopbarContextValue | null>(null);

export function TopbarProvider({ children }: { children: ReactNode }) {
  const [content, setContent] = useState<ReactNode | null>(null);
  const [rightContent, setRightContent] = useState<ReactNode | null>(null);
  const value = useMemo(
    () => ({ content, setContent, rightContent, setRightContent }),
    [content, rightContent]
  );
  return <TopbarContext.Provider value={value}>{children}</TopbarContext.Provider>;
}

export function useTopbarContent() {
  const ctx = useContext(TopbarContext);
  if (!ctx) {
    throw new Error("useTopbarContent must be used within TopbarProvider");
  }
  return ctx;
}
