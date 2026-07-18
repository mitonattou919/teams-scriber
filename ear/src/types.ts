export interface EarConfig {
  token: string;
  meetingLink: string;
  wsUrl: string;
}

export interface CaptionMessage {
  speaker: string;
  text: string;
  resultType: 'Partial' | 'Final';
  timestamp: string;
}
