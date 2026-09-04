// Pure local queue: which invoice is current, which are done (optimistically), and how to move.

export interface QueueState {
  ids: string[];
  index: number;
  done: string[];
}

export type QueueAction =
  | { type: "ids"; ids: string[] }
  | { type: "next" }
  | { type: "previous" }
  | { type: "markDone"; id: string }
  | { type: "unmarkDone"; id: string };

export const EMPTY_QUEUE: QueueState = { ids: [], index: 0, done: [] };

function nextUndoneIndex(state: QueueState, from: number, step: 1 | -1): number {
  for (let i = from + step; i >= 0 && i < state.ids.length; i += step) {
    if (!state.done.includes(state.ids[i])) return i;
  }
  return state.index;
}

export function queueReducer(state: QueueState, action: QueueAction): QueueState {
  switch (action.type) {
    case "ids": {
      const ids = action.ids.filter((id, i) => action.ids.indexOf(id) === i);
      const currentId = state.ids[state.index];
      const keptIndex = currentId ? ids.indexOf(currentId) : -1;
      return { ...state, ids, index: keptIndex >= 0 ? keptIndex : Math.min(state.index, Math.max(ids.length - 1, 0)) };
    }
    case "next":
      return { ...state, index: nextUndoneIndex(state, state.index, 1) };
    case "previous":
      return { ...state, index: nextUndoneIndex(state, state.index, -1) };
    case "markDone": {
      if (state.done.includes(action.id)) return state;
      const done = [...state.done, action.id];
      const marked = { ...state, done };
      const forward = nextUndoneIndex(marked, state.index, 1);
      const index = forward !== state.index ? forward : nextUndoneIndex(marked, state.index, -1);
      return { ...marked, index };
    }
    case "unmarkDone": {
      const done = state.done.filter((id) => id !== action.id);
      const index = state.ids.indexOf(action.id);
      return { ...state, done, index: index >= 0 ? index : state.index };
    }
  }
}

export function currentId(state: QueueState): string | null {
  const id = state.ids[state.index];
  if (!id || state.done.includes(id)) return null;
  return id;
}

export function remainingCount(state: QueueState): number {
  return state.ids.filter((id) => !state.done.includes(id)).length;
}
