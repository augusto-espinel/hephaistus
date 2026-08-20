export interface SchematicState {
  path: string
  hash: string
  component_count: number
  net_count: number
  components: Component[]
  nets: Net[]
  directives: Directive[]
  last_modified: string | null
}

export interface Component {
  reference: string
  lib_id: string
  value?: string
  footprint?: string
  pins: Pin[]
}

export interface Pin {
  number: string
  name: string
  net: string
}

export interface Net {
  name: string
  pins: string[]
}

export interface Directive {
  directive_type: string
  text: string
}