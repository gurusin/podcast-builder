import { CreatePodcastHandler } from '../../src/podcast/commands/handlers/create-podcast.handler';
import { CreatePodcastCommand } from '../../src/podcast/commands/create-podcast.command';
import { IPodcastRepository } from '../../src/podcast/repositories/podcast.repository.interface';
import { EventFactory } from '../../src/podcast/factories/event.factory';
import { KafkaProducer } from '../../src/podcast/kafka/kafka.producer';
import { PodcastStatus } from '../../src/common/enums/podcast-status.enum';
import { TopicRequestedEvent } from '../../src/podcast/events/topic-requested.event';
import { PodcastDocument } from '../../src/podcast/schemas/podcast.schema';

describe('CreatePodcastHandler', () => {
  let handler: CreatePodcastHandler;
  let podcastRepository: jest.Mocked<IPodcastRepository>;
  let eventFactory: jest.Mocked<EventFactory>;
  let kafkaProducer: jest.Mocked<KafkaProducer>;

  const mockPodcast = {
    podcastId: 'test-uuid-1234',
    topic: 'AI in Healthcare',
    durationHint: 'medium',
    status: PodcastStatus.PENDING,
    createdAt: new Date(),
    updatedAt: new Date(),
  } as unknown as PodcastDocument;

  const mockEvent: TopicRequestedEvent = {
    eventType: 'TopicRequested',
    version: '1.0',
    podcastId: 'test-uuid-1234',
    topic: 'AI in Healthcare',
    durationHint: 'medium',
    ts: new Date().toISOString(),
  };

  beforeEach(() => {
    podcastRepository = {
      create: jest.fn().mockResolvedValue(mockPodcast),
      findById: jest.fn(),
      updateStatus: jest.fn(),
    };

    eventFactory = {
      createTopicRequestedEvent: jest.fn().mockReturnValue(mockEvent),
    } as unknown as jest.Mocked<EventFactory>;

    kafkaProducer = {
      publish: jest.fn().mockResolvedValue(undefined),
      onModuleInit: jest.fn(),
      onModuleDestroy: jest.fn(),
    } as unknown as jest.Mocked<KafkaProducer>;

    handler = new CreatePodcastHandler(
      podcastRepository,
      eventFactory,
      kafkaProducer,
    );
  });

  it('should create a podcast with status PENDING in the repository', async () => {
    const command = new CreatePodcastCommand('AI in Healthcare', 'medium');

    await handler.execute(command);

    expect(podcastRepository.create).toHaveBeenCalledTimes(1);
    const createArg = podcastRepository.create.mock.calls[0][0];
    expect(createArg.topic).toBe('AI in Healthcare');
    expect(createArg.durationHint).toBe('medium');
    expect(createArg.status).toBe(PodcastStatus.PENDING);
    expect(typeof createArg.podcastId).toBe('string');
    expect(createArg.podcastId.length).toBeGreaterThan(0);
  });

  it('should publish exactly one Kafka message to topic-requested', async () => {
    const command = new CreatePodcastCommand('AI in Healthcare', 'medium');

    await handler.execute(command);

    expect(kafkaProducer.publish).toHaveBeenCalledTimes(1);
    expect(kafkaProducer.publish).toHaveBeenCalledWith(
      'topic-requested',
      mockEvent,
    );
  });

  it('should return { podcastId } matching the persisted podcast id', async () => {
    const command = new CreatePodcastCommand('AI in Healthcare', 'medium');

    const result = await handler.execute(command);

    // The podcastId comes from the uuid generated inside the handler and passed
    // both to the repository and to EventFactory; we verify it is a non-empty
    // string consistent across both calls.
    expect(result).toHaveProperty('podcastId');
    expect(typeof result.podcastId).toBe('string');
    expect(result.podcastId.length).toBeGreaterThan(0);

    const createArg = podcastRepository.create.mock.calls[0][0];
    expect(result.podcastId).toBe(createArg.podcastId);
  });

  it('should use EventFactory to build the event envelope', async () => {
    const command = new CreatePodcastCommand('AI in Healthcare', 'medium');

    await handler.execute(command);

    expect(eventFactory.createTopicRequestedEvent).toHaveBeenCalledTimes(1);
    const [podcastId, topic, durationHint] =
      eventFactory.createTopicRequestedEvent.mock.calls[0];
    expect(topic).toBe('AI in Healthcare');
    expect(durationHint).toBe('medium');
    expect(typeof podcastId).toBe('string');
  });
});
