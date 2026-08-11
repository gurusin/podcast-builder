import { Injectable } from '@nestjs/common';
import { INotificationStrategy } from './notification.strategy.interface';
import { PodcastGateway } from '../podcast.gateway';

/**
 * WebSocketNotificationStrategy (Strategy pattern — concrete implementation).
 * Delegates to PodcastGateway so that the transport detail (Socket.IO) is
 * fully encapsulated here.  Swapping to another channel requires only a new
 * strategy class, leaving the consumer and gateway untouched.
 */
@Injectable()
export class WebSocketNotificationStrategy implements INotificationStrategy {
  constructor(private readonly gateway: PodcastGateway) {}

  async notify(podcastId: string, status: string): Promise<void> {
    this.gateway.notifyStatus(podcastId, status);
  }
}
