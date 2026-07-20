export interface EarConfig {
  token: string;
  meetingLink: string;
  wsUrl: string;
}

export interface CaptionMessage {
  type: 'caption';
  speaker: string;
  text: string;
  resultType: 'Partial' | 'Final';
  timestamp: string;
}

export interface CallEndedMessage {
  type: 'call_ended';
  timestamp: string;
}

export type EarMessage = CaptionMessage | CallEndedMessage;
