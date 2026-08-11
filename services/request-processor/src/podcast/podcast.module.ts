import { Module } from '@nestjs/common';
import { CqrsModule } from '@nestjs/cqrs';
import { MongooseModule } from '@nestjs/mongoose';

import { Podcast, PodcastSchema } from './schemas/podcast.schema';
import { PodcastRepository } from './repositories/podcast.repository';
import { PODCAST_REPOSITORY } from './repositories/podcast.repository.interface';
import { EventFactory } from './factories/event.factory';
import { KafkaProducer } from './kafka/kafka.producer';
import { KafkaConsumer } from './kafka/kafka.consumer';
import { PodcastGateway } from './podcast.gateway';
import {
  NOTIFICATION_STRATEGY,
} from './strategies/notification.strategy.interface';
import { WebSocketNotificationStrategy } from './strategies/websocket-notification.strategy';
import { CreatePodcastHandler } from './commands/handlers/create-podcast.handler';
import { GetPodcastStatusHandler } from './queries/handlers/get-podcast-status.handler';
import { PodcastController } from './podcast.controller';

const CommandHandlers = [CreatePodcastHandler];
const QueryHandlers = [GetPodcastStatusHandler];

@Module({
  imports: [
    CqrsModule,
    MongooseModule.forFeature([
      { name: Podcast.name, schema: PodcastSchema },
    ]),
  ],
  controllers: [PodcastController],
  providers: [
    // Repository (Repository pattern) — bound behind an injection token
    {
      provide: PODCAST_REPOSITORY,
      useClass: PodcastRepository,
    },
    // Notification strategy (Strategy pattern) — bound behind an injection token
    {
      provide: NOTIFICATION_STRATEGY,
      useClass: WebSocketNotificationStrategy,
    },
    // Infrastructure
    EventFactory,
    KafkaProducer,
    KafkaConsumer,
    PodcastGateway,
    // CQRS handlers
    ...CommandHandlers,
    ...QueryHandlers,
  ],
})
export class PodcastModule {}
