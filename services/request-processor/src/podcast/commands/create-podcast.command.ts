export class CreatePodcastCommand {
  constructor(
    public readonly topic: string,
    public readonly durationHint: 'short' | 'medium' | 'long',
  ) {}
}
