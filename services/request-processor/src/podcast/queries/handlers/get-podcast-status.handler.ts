import { IQueryHandler, QueryHandler } from '@nestjs/cqrs';
import { Inject, NotFoundException } from '@nestjs/common';
import { GetPodcastStatusQuery } from '../get-podcast-status.query';
import {
  IPodcastRepository,
  PODCAST_REPOSITORY,
} from '../../repositories/podcast.repository.interface';
import { PodcastDocument } from '../../schemas/podcast.schema';

/**
 * CQRS QueryHandler — handles the read side of the CQRS split.
 * Pure query: no side effects, only data retrieval.
 */
@QueryHandler(GetPodcastStatusQuery)
export class GetPodcastStatusHandler
  implements IQueryHandler<GetPodcastStatusQuery, PodcastDocument>
{
  constructor(
    @Inject(PODCAST_REPOSITORY)
    private readonly podcastRepository: IPodcastRepository,
  ) {}

  async execute(query: GetPodcastStatusQuery): Promise<PodcastDocument> {
    const podcast = await this.podcastRepository.findById(query.podcastId);

    if (!podcast) {
      throw new NotFoundException(
        `Podcast with id "${query.podcastId}" not found`,
      );
    }

    return podcast;
  }
}
