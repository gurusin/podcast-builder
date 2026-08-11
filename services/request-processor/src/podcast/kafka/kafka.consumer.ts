import { Inject, Injectable, Logger, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
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

@Injectable()
export class KafkaConsumer implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(KafkaConsumer.name);
  private readonly kafka: Kafka;
  private readonly consumer: Consumer;
  private running = false;

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
      retry: { retries: 5, initialRetryTime: 300 },
    });
    this.consumer = this.kafka.consumer({ groupId: 'request-processor-group' });
  }

  // Non-blocking — starts retry loop in the background so the HTTP server
  // is never held up by a slow Kafka broker.
  onModuleInit(): void {
    void this.startWithRetry();
  }

  async onModuleDestroy(): Promise<void> {
    if (this.running) {
      await this.consumer.disconnect();
    }
  }

  private async startWithRetry(attempts = 10, delayMs = 3000): Promise<void> {
    for (let i = 1; i <= attempts; i++) {
      try {
        await this.consumer.connect();
        await this.consumer.subscribe({ topic: 'podcast-generated', fromBeginning: false });
        await this.consumer.run({
          eachMessage: async (payload: EachMessagePayload) => {
            await this.handleMessage(payload);
          },
        });
        this.running = true;
        this.logger.log('Kafka consumer connected and listening on podcast-generated');
        return;
      } catch (err) {
        this.logger.warn(`Kafka consumer connect attempt ${i}/${attempts} failed: ${(err as Error).message}`);
        if (i < attempts) await this.delay(delayMs);
      }
    }
    this.logger.error('Kafka consumer could not connect after all retries — status push via WebSocket will be unavailable');
  }

  private async handleMessage(payload: EachMessagePayload): Promise<void> {
    const raw = payload.message.value?.toString();
    if (!raw) return;

    try {
      const event = JSON.parse(raw) as PodcastGeneratedEvent;
      await this.podcastRepository.updateStatus(event.podcastId, PodcastStatus.DONE, event.filePath);
      await this.notificationStrategy.notify(event.podcastId, PodcastStatus.DONE);
    } catch (err) {
      this.logger.error(`Failed to handle podcast-generated message: ${(err as Error).message}`);
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
