import { CommandHandler, ICommandHandler } from '@nestjs/cqrs';
import { Inject } from '@nestjs/common';
import { v4 as uuidv4 } from 'uuid';
import { CreatePodcastCommand } from '../create-podcast.command';
import {
  IPodcastRepository,
  PODCAST_REPOSITORY,
} from '../../repositories/podcast.repository.interface';
import { EventFactory } from '../../factories/event.factory';
import { KafkaProducer } from '../../kafka/kafka.producer';
import { PodcastStatus } from '../../../common/enums/podcast-status.enum';

export interface CreatePodcastResult {
  podcastId: string;
}

/**
 * CQRS CommandHandler — handles the write side of the CQRS split.
 * Orchestrates: persist → build event (Factory) → publish (Observer/Kafka).
 */
@CommandHandler(CreatePodcastCommand)
export class CreatePodcastHandler
  implements ICommandHandler<CreatePodcastCommand, CreatePodcastResult>
{
  constructor(
    @Inject(PODCAST_REPOSITORY)
    private readonly podcastRepository: IPodcastRepository,
    private readonly eventFactory: EventFactory,
    private readonly kafkaProducer: KafkaProducer,
  ) {}

  async execute(command: CreatePodcastCommand): Promise<CreatePodcastResult> {
    const podcastId = uuidv4();
    const now = new Date();

    await this.podcastRepository.create({
      podcastId,
      topic: command.topic,
      durationHint: command.durationHint,
      status: PodcastStatus.PENDING,
      createdAt: now,
      updatedAt: now,
    });

    const event = this.eventFactory.createTopicRequestedEvent(
      podcastId,
      command.topic,
      command.durationHint,
    );

    await this.kafkaProducer.publish('topic-requested', event);

    return { podcastId };
  }
}
