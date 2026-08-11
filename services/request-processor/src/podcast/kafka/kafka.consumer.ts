import { Inject, Injectable, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { Kafka, Consumer, EachMessagePayload } from 'kafkajs';
import { PodcastGeneratedEvent } from '../events/podcast-generated.event';
import {
  IPodcastRepository,
  PODCAST_REPOSITORY,
} from '../repositories/podcast.repository.interface';
import {
  INotificationStrategy,
  NOTIFICATION_STRATEGY,
} from '../strategies/notification.strategy.interface';
import { PodcastStatus } from '../../common/enums/podcast-status.enum';

/**
 * KafkaConsumer (Observer pattern — subscriber side).
 * Subscribes to `podcast-generated`, updates the repository (write model) and
 * then delegates real-time notification to the injected INotificationStrategy
 * (Strategy pattern).  No concrete strategy is referenced here — DIP upheld.
 */
@Injectable()
export class KafkaConsumer implements OnModuleInit, OnModuleDestroy {
  private readonly kafka: Kafka;
  private readonly consumer: Consumer;

  constructor(
    @Inject(PODCAST_REPOSITORY)
    private readonly podcastRepository: IPodcastRepository,
    @Inject(NOTIFICATION_STRATEGY)
    private readonly notificationStrategy: INotificationStrategy,
  ) {
    const broker = process.env.KAFKA_BROKER ?? 'kafka:9092';
    this.kafka = new Kafka({
      clientId: 'request-processor-consumer',
      brokers: [broker],
    });
    this.consumer = this.kafka.consumer({
      groupId: 'request-processor-group',
    });
  }

  async onModuleInit(): Promise<void> {
    await this.consumer.connect();
    await this.consumer.subscribe({
      topic: 'podcast-generated',
      fromBeginning: false,
    });

    await this.consumer.run({
      eachMessage: async (payload: EachMessagePayload): Promise<void> => {
        await this.handleMessage(payload);
      },
    });
  }

  private async handleMessage(payload: EachMessagePayload): Promise<void> {
    const raw = payload.message.value?.toString();
    if (!raw) return;

    const event: PodcastGeneratedEvent = JSON.parse(raw) as PodcastGeneratedEvent;

    await this.podcastRepository.updateStatus(
      event.podcastId,
      PodcastStatus.DONE,
      event.filePath,
    );

    await this.notificationStrategy.notify(event.podcastId, PodcastStatus.DONE);
  }

  async onModuleDestroy(): Promise<void> {
    await this.consumer.disconnect();
  }
}
