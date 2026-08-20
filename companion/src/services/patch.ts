export interface PatchPlan {
  schema: 'hephaistus/patch-plan/v1'
  intent: string
  operations: PatchOperation[]
  rationale: string
}

export type PatchOperation =
  | PinAssignNetOperation
  | NetSplitOperation
  | ComponentAddOperation
  | ComponentUpdateOperation
  | ComponentRemoveOperation
  | SimulationSetDirectiveOperation
  | SimulationRemoveDirectiveOperation

export interface PinAssignNetOperation {
  type: 'pin.assign_net'
  reference: string
  pin: string
  net: string
}

export interface NetSplitOperation {
  type: 'net.split'
  origin_net: string
  move_pins: string[]
  new_net: string
}

export interface ComponentAddOperation {
  type: 'component.add'
  component: {
    reference: string
    lib_id: string
    value?: string
    pins: Record<string, string>
  }
}

export interface ComponentUpdateOperation {
  type: 'component.update_value'
  reference: string
  value: string
}

export interface ComponentRemoveOperation {
  type: 'component.remove'
  reference: string
}

export interface SimulationSetDirectiveOperation {
  type: 'simulation.set_directive'
  directive: 'tran' | 'ac' | 'dc' | 'op' | 'options'
  parameters: Record<string, string>
}

export interface SimulationRemoveDirectiveOperation {
  type: 'simulation.remove_directive'
  directive: 'tran' | 'ac' | 'dc' | 'op' | 'options'
}