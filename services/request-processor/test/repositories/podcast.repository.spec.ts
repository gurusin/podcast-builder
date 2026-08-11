import { PodcastRepository } from '../../src/podcast/repositories/podcast.repository';
import { PodcastStatus } from '../../src/common/enums/podcast-status.enum';
import { PodcastDocument } from '../../src/podcast/schemas/podcast.schema';
import { CreatePodcastData } from '../../src/podcast/repositories/podcast.repository.interface';

/**
 * Lightweight Mongoose Model stub.  We use a class so that `new modelMock()`
 * works and returns an instance with a `save` method — mirroring how the
 * real PodcastRepository calls `new this.podcastModel(data)`.
 */
function buildModelMock(savedDoc: PodcastDocument) {
  class ModelMock {
    save = jest.fn().mockResolvedValue(savedDoc);

    static findOne = jest.fn();
    static findOneAndUpdate = jest.fn();
  }

  return ModelMock as unknown as jest.Mocked<typeof ModelMock> & {
    new (): { save: jest.Mock };
  };
}

describe('PodcastRepository', () => {
  const baseDoc = {
    podcastId: 'repo-test-id',
    topic: 'Space Exploration',
    durationHint: 'medium',
    status: PodcastStatus.PENDING,
    createdAt: new Date(),
    updatedAt: new Date(),
  } as unknown as PodcastDocument;

  describe('create', () => {
    it('should instantiate a model and call save, returning the saved document', async () => {
      const ModelMock = buildModelMock(baseDoc);
      const repo = new PodcastRepository(ModelMock as never);

      const data: CreatePodcastData = {
        podcastId: 'repo-test-id',
        topic: 'Space Exploration',
        durationHint: 'medium',
        status: PodcastStatus.PENDING,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      const result = await repo.create(data);

      expect(result).toBe(baseDoc);
    });
  });

  describe('findById', () => {
    it('should return the matching document when found', async () => {
      const ModelMock = buildModelMock(baseDoc);
      (ModelMock.findOne as jest.Mock).mockReturnValue({
        exec: jest.fn().mockResolvedValue(baseDoc),
      });

      const repo = new PodcastRepository(ModelMock as never);
      const result = await repo.findById('repo-test-id');

      expect(ModelMock.findOne).toHaveBeenCalledWith({ podcastId: 'repo-test-id' });
      expect(result).toBe(baseDoc);
    });

    it('should return null when the document is not found', async () => {
      const ModelMock = buildModelMock(baseDoc);
      (ModelMock.findOne as jest.Mock).mockReturnValue({
        exec: jest.fn().mockResolvedValue(null),
      });

      const repo = new PodcastRepository(ModelMock as never);
      const result = await repo.findById('missing-id');

      expect(result).toBeNull();
    });
  });

  describe('updateStatus', () => {
    it('should call findOneAndUpdate with the correct filter, update, and new:true', async () => {
      const updatedDoc = {
        ...baseDoc,
        status: PodcastStatus.DONE,
        filePath: '/audio/ep1.mp3',
      } as unknown as PodcastDocument;

      const ModelMock = buildModelMock(baseDoc);
      (ModelMock.findOneAndUpdate as jest.Mock).mockReturnValue({
        exec: jest.fn().mockResolvedValue(updatedDoc),
      });

      const repo = new PodcastRepository(ModelMock as never);
      const result = await repo.updateStatus(
        'repo-test-id',
        PodcastStatus.DONE,
        '/audio/ep1.mp3',
      );

      expect(ModelMock.findOneAndUpdate).toHaveBeenCalledWith(
        { podcastId: 'repo-test-id' },
        expect.objectContaining({
          $set: expect.objectContaining({
            status: PodcastStatus.DONE,
            filePath: '/audio/ep1.mp3',
          }),
        }),
        { new: true },
      );
      expect(result).toBe(updatedDoc);
    });

    it('should omit filePath from the update when not provided', async () => {
      const ModelMock = buildModelMock(baseDoc);
      (ModelMock.findOneAndUpdate as jest.Mock).mockReturnValue({
        exec: jest.fn().mockResolvedValue(baseDoc),
      });

      const repo = new PodcastRepository(ModelMock as never);
      await repo.updateStatus('repo-test-id', PodcastStatus.GENERATING);

      const updateArg = (ModelMock.findOneAndUpdate as jest.Mock).mock.calls[0][1];
      expect(updateArg.$set).not.toHaveProperty('filePath');
    });
  });
});
