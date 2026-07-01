/*
 * Copyright (c) 2026 openEuler
 * Witty OpenCode is licensed under Mulan PSL v2.
 * You can use this software according to the terms and conditions of the Mulan PSL v2.
 * You may obtain a copy of Mulan PSL v2 at:
 *          http://license.coscl.org.cn/MulanPSL2
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
 * EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
 * MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
 * See the Mulan PSL v2 for more details.
 */

// @ts-nocheck
/** @jsxImportSource @opentui/solid */
import { type JSX } from "@opentui/solid"
import type { TuiPlugin, TuiPluginModule, TuiSlotPlugin } from "@opencode-ai/plugin/tui"

type Opts = {
  enabled: boolean
}

const art = [
  "██╗    ██╗██╗████████╗████████╗██╗   ██╗",
  "██║    ██║██║╚══██╔══╝╚══██╔══╝╚██╗ ██╔╝",
  "██║ █╗ ██║██║   ██║      ██║    ╚████╔╝ ",
  "██║███╗██║██║   ██║      ██║     ╚██╔╝  ",
  "╚███╔███╔╝██║   ██║      ██║      ██║   ",
  " ╚══╝╚══╝ ╚═╝   ╚═╝      ╚═╝      ╚═╝   ",
]

const ramp = ["#AF5FFF", "#00AFFF", "#AFFFFF"]

const num = (value: string, start: number) => {
  return Number.parseInt(value.slice(start, start + 2), 16)
}

const cfg = (options: Record<string, unknown> | undefined): Opts => {
  return {
    enabled: options?.enabled !== false,
  }
}

const mix = (a: string, b: string, t: number) => {
  const r = Math.round(num(a, 1) + (num(b, 1) - num(a, 1)) * t)
  const g = Math.round(num(a, 3) + (num(b, 3) - num(a, 3)) * t)
  const b0 = Math.round(num(a, 5) + (num(b, 5) - num(a, 5)) * t)
  return `#${[r, g, b0].map((v) => v.toString(16).padStart(2, "0")).join("")}`
}

const fill = (i: number, size: number) => {
  if (size <= 1) return ramp[0]
  const t = i / (size - 1)
  if (t <= 0.5) return mix(ramp[0], ramp[1], t * 2)
  return mix(ramp[1], ramp[2], (t - 0.5) * 2)
}

const line = (value: string, size: number) => {
  return (
    <text wrapMode="none">
      {Array.from(value).map((char, i) => (
        <span style={{ fg: fill(i, size) }}>{char}</span>
      ))}
    </text>
  )
}

const slot = (_input: Opts): TuiSlotPlugin => ({
  slots: {
    home_logo(): JSX.Element {
      const size = Math.max(...art.map((item) => Array.from(item).length))

      return (
        <box flexDirection="column" alignItems="center">
          {art.map((item) => line(item, size))}
        </box>
      )
    },
  },
})

const tui: TuiPlugin = async (api, options) => {
  const input = cfg(options ?? undefined)
  if (!input.enabled) return
  api.slots.register(slot(input))
}

const plugin: TuiPluginModule & { id: string } = {
  id: "home-logo",
  tui,
}

export default plugin
