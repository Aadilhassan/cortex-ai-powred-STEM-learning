export type WSMessage =
  | { type: 'text_delta'; content: string }
  | { type: 'audio_chunk'; data: string }
  | { type: 'diagram'; mermaid: string }
  | { type: 'transcript'; content: string }
  | { type: 'sources'; sources: unknown[] }
  | { type: 'done' };

export class StudySocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnect = 5;
  private wsPath: string;

  constructor(
    idOrPath: string,
    private onMessage: (msg: WSMessage) => void,
    private onConnect?: () => void,
    private onDisconnect?: () => void,
    /** If provided, use this as the full WS path instead of /ws/chat/{id} */
    customPath?: string,
  ) {
    this.wsPath = customPath || `/ws/chat/${idOrPath}`;
  }

  connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.ws = new WebSocket(`${protocol}//${location.host}${this.wsPath}`);

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

  send(content: string, mode?: string) {
    this.ws?.send(JSON.stringify({ content, mode }));
  }

  sendRaw(data: Record<string, unknown>) {
    this.ws?.send(JSON.stringify(data));
  }

  disconnect() {
    this.maxReconnect = 0;
    this.ws?.close();
  }
}
