import { PodcastStatus } from '../../common/enums/podcast-status.enum';
import { PodcastDocument } from '../schemas/podcast.schema';

export interface CreatePodcastData {
  podcastId: string;
  topic: string;
  durationHint: string;
  status: PodcastStatus;
  createdAt: Date;
  updatedAt: Date;
}

export interface IPodcastRepository {
  create(data: CreatePodcastData): Promise<PodcastDocument>;
  findById(podcastId: string): Promise<PodcastDocument | null>;
  updateStatus(
    podcastId: string,
    status: PodcastStatus,
    filePath?: string,
  ): Promise<PodcastDocument | null>;
}

export const PODCAST_REPOSITORY = 'PODCAST_REPOSITORY';
