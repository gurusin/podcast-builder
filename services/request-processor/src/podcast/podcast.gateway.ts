import {
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';

/**
 * PodcastGateway exposes a Socket.IO server.  It is a pure infrastructure
 * adapter: business logic lives in the notification strategy, not here.
 */
@WebSocketGateway({ cors: true })
export class PodcastGateway {
  @WebSocketServer()
  server: Server;

  notifyStatus(podcastId: string, status: string): void {
    this.server.emit('podcast:status', { podcastId, status });
  }
}
