export interface TopicRequestedEvent {
  eventType: 'TopicRequested';
  version: '1.0';
  podcastId: string;
  topic: string;
  durationHint: 'short' | 'medium' | 'long';
  ts: string;
}
