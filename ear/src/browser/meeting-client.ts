import { CallClient, Features, type Call, type TeamsCaptions } from '@azure/communication-calling';
import { AzureCommunicationTokenCredential } from '@azure/communication-common';
import type { EarConfig, CaptionMessage } from '../types';

declare global {
  interface Window {
    __EAR_CONFIG__: EarConfig;
  }
}

function log(...args: unknown[]): void {
  console.log('[ear:browser]', ...args);
}

async function connectBrainSocket(wsUrl: string): Promise<WebSocket> {
  const ws = new WebSocket(wsUrl);
  await new Promise<void>((resolve, reject) => {
    ws.addEventListener('open', () => resolve(), { once: true });
    ws.addEventListener('error', () => reject(new Error('failed to connect to brain WebSocket')), { once: true });
  });
  return ws;
}

async function startCaptions(call: Call, ws: WebSocket): Promise<void> {
  const captionsFeature = call.feature(Features.Captions);
  const captions = captionsFeature.captions;
  if (captions.kind !== 'TeamsCaptions') {
    log('captions not available for this call, kind =', captions.kind);
    return;
  }
  // captionsFeature.captions is typed as the generic CaptionsCommon; narrow it
  // ourselves since the SDK does not expose captions as a discriminated union.
  const teamsCaptions = captions as TeamsCaptions;

  teamsCaptions.on('CaptionsReceived', (data) => {
    if (data.resultType !== 'Final') {
      return;
    }
    const message: CaptionMessage = {
      speaker: data.speaker.displayName ?? '(unknown)',
      text: data.spokenText,
      resultType: data.resultType,
      timestamp: data.timestamp.toISOString(),
    };
    log('caption:', message.speaker, message.text, message.resultType, message.timestamp);
    ws.send(JSON.stringify(message));
  });

  await teamsCaptions.startCaptions({ spokenLanguage: 'ja-jp' });
  log('captions started');
}

async function main(): Promise<void> {
  const config = window.__EAR_CONFIG__;

  const ws = await connectBrainSocket(config.wsUrl);
  log('connected to brain WebSocket');

  const tokenCredential = new AzureCommunicationTokenCredential(config.token);
  const callClient = new CallClient();
  const callAgent = await callClient.createCallAgent(tokenCredential, {
    displayName: 'AI-Facilitator (transcribing)',
  });

  const call = callAgent.join({ meetingLink: config.meetingLink }, { audioOptions: { muted: true } });

  call.on('stateChanged', () => {
    log('call state:', call.state);
    if (call.state === 'Connected') {
      startCaptions(call, ws).catch((error) => log('failed to start captions:', error));
    }
    if (call.state === 'Disconnected') {
      log('call disconnected');
    }
  });
}

main().catch((error) => {
  log('fatal error:', error);
});
