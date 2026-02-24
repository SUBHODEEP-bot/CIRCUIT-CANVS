import { useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import type { Module, ModulePin, CanvasModuleInstance, SelectedPin } from "@/lib/circuit-types";
import { PIN_TYPE_COLORS as pinColors, MODULE_DISPLAY_WIDTH } from "@/lib/circuit-types";

interface ModuleNodeProps {
  instance: CanvasModuleInstance;
  module: Module;
  pins: ModulePin[];
  selectedPin: SelectedPin | null;
  scale: number;
  onMouseDown: (instanceId: string, e: React.MouseEvent) => void;
  onPinClick: (instanceId: string, pinId: string) => void;
  onHeightReady?: (moduleId: string, height: number) => void;
}

/**
 * Individual module component rendered on the canvas
 * Shows module image at its natural aspect ratio with clickable pin zones
 */
export default function ModuleNode({
  instance,
  module,
  pins,
  selectedPin,
  scale,
  onMouseDown,
  onPinClick,
  onHeightReady,
}: ModuleNodeProps) {
  const [imgHeight, setImgHeight] = useState<number>(MODULE_DISPLAY_WIDTH);

  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    const aspect = img.naturalHeight / img.naturalWidth;
    const h = MODULE_DISPLAY_WIDTH * aspect;
    setImgHeight(h);
    onHeightReady?.(module.id, h);
  };

  // Report default height for modules without images
  useEffect(() => {
    if (!module.image_url) {
      onHeightReady?.(module.id, 100);
    }
  }, [module.id, module.image_url, onHeightReady]);

  const displayHeight = module.image_url ? imgHeight : 100;

  return (
    <div
      className="module-node absolute select-none"
      style={{
        left: instance.x,
        top: instance.y,
        width: MODULE_DISPLAY_WIDTH,
        zIndex: 10,
      }}
      onMouseDown={(e) => {
        if (e.button === 0 && !(e.target as HTMLElement).closest('.pin-zone')) {
          onMouseDown(instance.instanceId, e);
        }
      }}
    >
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        {/* Module image area - sized to natural aspect ratio */}
        <div
          className="relative bg-muted/30"
          style={{ width: MODULE_DISPLAY_WIDTH, height: displayHeight }}
        >
          {module.image_url ? (
            <img
              src={module.image_url}
              alt={module.name}
              className="w-full h-full object-fill"
              draggable={false}
              onLoad={handleImageLoad}
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <Cpu className="h-10 w-10 text-muted-foreground" />
            </div>
          )}

          {/* Pin zones overlay */}
          {pins.map(pin => {
            const isSelected =
              selectedPin?.instanceId === instance.instanceId &&
              selectedPin?.pinId === pin.id;
            const pinColor = pinColors[pin.pin_type];

            return (
              <div
                key={pin.id}
                className={`pin-zone absolute rounded-full border-2 ${isSelected ? 'active' : ''}`}
                style={{
                  left: `${pin.x}%`,
                  top: `${pin.y}%`,
                  width: 12,
                  height: 12,
                  marginLeft: -6,
                  marginTop: -6,
                  backgroundColor: pinColor,
                  borderColor: isSelected ? '#ffffff' : pinColor,
                  boxShadow: isSelected ? `0 0 8px ${pinColor}` : 'none',
                }}
                title={`${pin.name} (${pin.pin_type})`}
                onClick={(e) => {
                  e.stopPropagation();
                  onPinClick(instance.instanceId, pin.id);
                }}
              />
            );
          })}
        </div>

        {/* Module label */}
        <div className="px-2 py-1.5 border-t border-border">
          <p className="text-[10px] font-mono text-card-foreground truncate text-center">
            {module.name}
          </p>
        </div>
      </div>
    </div>
  );
}
