export type WSMessage =
  | { type: 'text_delta'; content: string }
  | { type: 'audio_chunk'; data: string }
  | { type: 'diagram'; mermaid: string }
  | { type: 'done' };

export class StudySocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnect = 5;

  constructor(
    private subtopicId: string,
    private onMessage: (msg: WSMessage) => void,
    private onConnect?: () => void,
    private onDisconnect?: () => void,
  ) {}

  connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.ws = new WebSocket(`${protocol}//${location.host}/ws/chat/${this.subtopicId}`);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.onConnect?.();
    };

    this.ws.onmessage = (e) => {
      const msg: WSMessage = JSON.parse(e.data);
      this.onMessage(msg);
    };

    this.ws.onclose = () => {
      this.onDisconnect?.();
      if (this.reconnectAttempts < this.maxReconnect) {
        const delay = Math.pow(2, this.reconnectAttempts) * 1000;
        this.reconnectAttempts++;
        setTimeout(() => this.connect(), delay);
      }
    };
  }

  send(content: string) {
    this.ws?.send(JSON.stringify({ content }));
  }

  disconnect() {
    this.maxReconnect = 0;
    this.ws?.close();
  }
}
