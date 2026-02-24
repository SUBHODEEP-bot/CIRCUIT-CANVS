import { Cpu, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Module } from "@/lib/circuit-types";

interface ModuleSidebarProps {
  modules: Module[];
  onAddModule: (moduleId: string) => void;
}

/**
 * Sidebar panel showing available modules to add to the canvas
 */
export default function ModuleSidebar({ modules, onAddModule }: ModuleSidebarProps) {
  return (
    <div className="w-56 border-r border-border bg-card flex flex-col h-full">
      <div className="p-3 border-b border-border">
        <h3 className="text-sm font-semibold text-card-foreground">Modules</h3>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {modules.length === 0 ? (
          <p className="text-xs text-muted-foreground p-2 text-center">No modules available</p>
        ) : (
          modules.map(mod => (
            <button
              key={mod.id}
              className="w-full flex items-center gap-2 rounded-md px-2 py-2 text-left text-sm hover:bg-accent/20 transition-colors group"
              onClick={() => onAddModule(mod.id)}
            >
              <div className="w-8 h-8 rounded bg-muted flex items-center justify-center flex-shrink-0 overflow-hidden">
                {mod.image_url ? (
                  <img src={mod.image_url} alt={mod.name} className="w-full h-full object-contain" />
                ) : (
                  <Cpu className="h-4 w-4 text-muted-foreground" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-card-foreground truncate text-xs font-medium">{mod.name}</p>
                {mod.category && (
                  <p className="text-muted-foreground text-[10px] font-mono">{mod.category}</p>
                )}
              </div>
              <Plus className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </button>
          ))
        )}
      </div>
    </div>
  );
}
