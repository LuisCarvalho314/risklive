import type { ReactNode } from "react";

import { ShellClient } from "@/components/layout/shell-client";

export function Shell({ children }: { children: ReactNode }) {
  return <ShellClient>{children}</ShellClient>;
}
