import { Injectable } from '@nestjs/common';
import { TopicRequestedEvent } from '../events/topic-requested.event';

/**
 * EventFactory (Factory pattern) — centralises construction of all versioned
 * Kafka event envelopes.  No raw object literals scattered across command
 * handlers; every producer goes through this class so the shape is enforced
 * in a single place and remains consistent with the integration contract.
 */
@Injectable()
export class EventFactory {
  createTopicRequestedEvent(
    podcastId: string,
    topic: string,
    durationHint: 'short' | 'medium' | 'long',
  ): TopicRequestedEvent {
    return {
      eventType: 'TopicRequested',
      version: '1.0',
      podcastId,
      topic,
      durationHint,
      ts: new Date().toISOString(),
    };
  }
}
