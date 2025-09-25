export type MessageRole = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: number;
  type?: 'text' | 'status';
}

export interface ReservationProposal {
  resource_id: string;
  start_time: string;
  end_time?: string;
  reservation_id?: string;
  note?: string;
}

export interface ToolEventPayload {
  type: 'tool';
  tool_name: string;
  output: Record<string, unknown>;
}

export interface StreamTokenEvent {
  type: 'token';
  content: string;
}

export interface StreamMessageEvent {
  type: 'message';
  content: string;
}

export interface StreamDoneEvent {
  type: 'done';
}

export type StreamEvent =
  | StreamTokenEvent
  | StreamMessageEvent
  | StreamDoneEvent
  | ToolEventPayload;

export type ReservationDecisionAction = 'confirm' | 'cancel';
