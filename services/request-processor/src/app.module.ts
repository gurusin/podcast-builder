import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { PodcastModule } from './podcast/podcast.module';

const mongoUri =
  process.env.MONGODB_URI ?? 'mongodb://mongo:27017/podcast-system';

@Module({
  imports: [
    MongooseModule.forRoot(mongoUri),
    PodcastModule,
  ],
})
export class AppModule {}
