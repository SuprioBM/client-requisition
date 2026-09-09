"use client";

import { useState } from "react";
import { Sidebar } from "./sidebar";
import { StatusBar } from "./status-bar";
import { Dialog, DialogContent } from "@/components/ui/dialog";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileNav, setMobileNav] = useState(false);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <div className="hidden md:block">
        <Sidebar />
      </div>

      <Dialog open={mobileNav} onOpenChange={setMobileNav}>
        <DialogContent className="left-0 top-0 h-full max-w-56 translate-x-0 translate-y-0 rounded-none border-y-0 border-l-0 p-0">
          <Sidebar onNavigate={() => setMobileNav(false)} />
        </DialogContent>
      </Dialog>

      <div className="flex min-w-0 flex-1 flex-col">
        <StatusBar onMenu={() => setMobileNav(true)} />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1600px] p-4 md:p-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
