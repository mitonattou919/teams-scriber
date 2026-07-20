import { CallClient, Features, type Call, type TeamsCaptions } from '@azure/communication-calling';
import { AzureCommunicationTokenCredential } from '@azure/communication-common';
import type { EarConfig, EarMessage } from '../types';

declare global {
  interface Window {
    __EAR_CONFIG__: EarConfig;
    __earNotifyDisconnected__?: () => void;
  }
}

function log(...args: unknown[]): void {
  console.log('[ear:browser]', ...args);
}

function connectBrainSocket(wsUrl: string): WebSocket {
  const ws = new WebSocket(wsUrl);
  ws.addEventListener('open', () => log('connected to brain WebSocket'));
  ws.addEventListener('error', () => log('brain WebSocket error'));
  ws.addEventListener('close', () => log('brain WebSocket closed'));
  return ws;
}

function send(ws: WebSocket, message: EarMessage): void {
  if (ws.readyState !== WebSocket.OPEN) {
    log('brain WebSocket not open, dropping message:', message);
    return;
  }
  ws.send(JSON.stringify(message));
}

// call切断直後にブラウザごと終了するため、送信データがまだソケットの送信
// バッファに残っている(ネットワークに乗り切っていない)うちにプロセスが
// 落ちるとcall_ended通知が脳に届かない。bufferedAmountが捌けるのを待ってから戻る。
async function sendAndFlush(ws: WebSocket, message: EarMessage, timeoutMs = 2000): Promise<void> {
  send(ws, message);
  const start = Date.now();
  while (ws.bufferedAmount > 0 && Date.now() - start < timeoutMs) {
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
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
    const message: EarMessage = {
      type: 'caption',
      speaker: data.speaker.displayName ?? '(unknown)',
      text: data.spokenText,
      resultType: data.resultType,
      timestamp: data.timestamp.toISOString(),
    };
    log('caption:', message.speaker, message.text, message.resultType, message.timestamp);
    send(ws, message);
  });

  await teamsCaptions.startCaptions({ spokenLanguage: 'ja-jp' });
  log('captions started');
}

async function main(): Promise<void> {
  const config = window.__EAR_CONFIG__;

  // 脳のWebSocketサーバーが未起動でも会議参加・キャプション取得は続行できるよう、
  // 接続はブロッキングにせずバックグラウンドで行う。
  const ws = connectBrainSocket(config.wsUrl);

  const tokenCredential = new AzureCommunicationTokenCredential(config.token);
  const callClient = new CallClient();
  const callAgent = await callClient.createCallAgent(tokenCredential, {
    displayName: 'AI-Facilitator (transcribing)',
  });

  const call = callAgent.join({ meetingLink: config.meetingLink }, { audioOptions: { muted: true } });

  let captionsStarted = false;
  call.on('stateChanged', () => {
    log('call state:', call.state);
    if (call.state === 'Connected' && !captionsStarted) {
      captionsStarted = true;
      startCaptions(call, ws).catch((error) => log('failed to start captions:', error));
    }
    if (call.state === 'Disconnected') {
      log('call disconnected');
      void sendAndFlush(ws, { type: 'call_ended', timestamp: new Date().toISOString() }).finally(() => {
        window.__earNotifyDisconnected__?.();
      });
    }
  });
}

main().catch((error) => {
  log('fatal error:', error);
});
