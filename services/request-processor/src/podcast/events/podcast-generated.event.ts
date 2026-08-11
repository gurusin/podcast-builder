export interface PodcastGeneratedEvent {
  eventType: 'PodcastGenerated';
  version: '1.0';
  podcastId: string;
  filePath: string;
  durationSecs: number;
  ts: string;
}
