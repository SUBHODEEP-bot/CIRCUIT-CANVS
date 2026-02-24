/**
 * CircuitForge Lab - Type Definitions
 * Core data structures for modules, pins, wires, and canvas state
 */

// === Database Entity Types ===

export interface Module {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  image_url: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ModulePin {
  id: string;
  module_id: string;
  name: string;
  pin_type: PinType;
  x: number; // percentage 0-100
  y: number; // percentage 0-100
  created_at: string;
}

export type PinType = 'Power' | 'Ground' | 'Digital' | 'Analog' | 'I2C' | 'SPI';

export interface Project {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  canvas_data: CanvasData;
  created_at: string;
  updated_at: string;
}

// === Canvas State Types ===

export interface CanvasModuleInstance {
  instanceId: string;
  moduleId: string;
  x: number;
  y: number;
}

export interface WireWaypoint {
  x: number;
  y: number;
}

export interface CanvasWire {
  id: string;
  fromInstanceId: string;
  fromPinId: string;
  toInstanceId: string;
  toPinId: string;
  color: string;
  waypoints?: WireWaypoint[];
}

export interface CanvasData {
  modules: CanvasModuleInstance[];
  wires: CanvasWire[];
}

// === UI State Types ===

export interface SelectedPin {
  instanceId: string;
  pinId: string;
}

export interface PinPosition {
  x: number;
  y: number;
}

// === Constants ===

export const WIRE_COLORS = [
  { name: 'Red', value: '#ef4444' },
  { name: 'Green', value: '#22c55e' },
  { name: 'Blue', value: '#3b82f6' },
  { name: 'Yellow', value: '#eab308' },
  { name: 'White', value: '#e2e8f0' },
  { name: 'Orange', value: '#f97316' },
  { name: 'Purple', value: '#a855f7' },
  { name: 'Cyan', value: '#06b6d4' },
];

export const PIN_TYPE_COLORS: Record<PinType, string> = {
  Power: '#ef4444',
  Ground: '#6b7280',
  Digital: '#3b82f6',
  Analog: '#22c55e',
  I2C: '#eab308',
  SPI: '#a855f7',
};

export const PIN_TYPES: PinType[] = ['Power', 'Ground', 'Digital', 'Analog', 'I2C', 'SPI'];

/** Default module display dimensions on canvas */
export const MODULE_DISPLAY_WIDTH = 160;
export const MODULE_DISPLAY_HEIGHT = 120;
