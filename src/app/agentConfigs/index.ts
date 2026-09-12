import { cabinPilotScenario } from './cabinPilot';

import type { RealtimeAgent } from '@openai/agents/realtime';

// Map of scenario key -> array of RealtimeAgent objects
export const allAgentSets: Record<string, RealtimeAgent[]> = {
  cabinPilot: cabinPilotScenario,
};

export const defaultAgentSetKey = 'cabinPilot';
