import { NotFoundException } from '@nestjs/common';
import { GetPodcastStatusHandler } from '../../src/podcast/queries/handlers/get-podcast-status.handler';
import { GetPodcastStatusQuery } from '../../src/podcast/queries/get-podcast-status.query';
import { IPodcastRepository } from '../../src/podcast/repositories/podcast.repository.interface';
import { PodcastStatus } from '../../src/common/enums/podcast-status.enum';
import { PodcastDocument } from '../../src/podcast/schemas/podcast.schema';

describe('GetPodcastStatusHandler', () => {
  let handler: GetPodcastStatusHandler;
  let podcastRepository: jest.Mocked<IPodcastRepository>;

  const mockPodcast = {
    podcastId: 'abc-123',
    topic: 'Quantum Computing',
    durationHint: 'long',
    status: PodcastStatus.GENERATING,
    createdAt: new Date(),
    updatedAt: new Date(),
  } as unknown as PodcastDocument;

  beforeEach(() => {
    podcastRepository = {
      create: jest.fn(),
      findById: jest.fn(),
      updateStatus: jest.fn(),
    };

    handler = new GetPodcastStatusHandler(podcastRepository);
  });

  describe('when the podcast exists', () => {
    it('should return the podcast document', async () => {
      podcastRepository.findById.mockResolvedValue(mockPodcast);

      const query = new GetPodcastStatusQuery('abc-123');
      const result = await handler.execute(query);

      expect(podcastRepository.findById).toHaveBeenCalledWith('abc-123');
      expect(result).toBe(mockPodcast);
      expect(result.podcastId).toBe('abc-123');
      expect(result.status).toBe(PodcastStatus.GENERATING);
    });
  });

  describe('when the podcast does not exist', () => {
    it('should throw NotFoundException', async () => {
      podcastRepository.findById.mockResolvedValue(null);

      const query = new GetPodcastStatusQuery('nonexistent-id');

      await expect(handler.execute(query)).rejects.toThrow(NotFoundException);
      await expect(handler.execute(query)).rejects.toThrow(
        'Podcast with id "nonexistent-id" not found',
      );
    });
  });
});
