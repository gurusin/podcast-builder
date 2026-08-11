import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument } from 'mongoose';
import { PodcastStatus } from '../../common/enums/podcast-status.enum';

export type PodcastDocument = HydratedDocument<Podcast>;

@Schema({ timestamps: false })
export class Podcast {
  @Prop({ required: true, unique: true, index: true })
  podcastId: string;

  @Prop({ required: true })
  topic: string;

  @Prop({ required: true })
  durationHint: string;

  @Prop({
    required: true,
    enum: Object.values(PodcastStatus),
    default: PodcastStatus.PENDING,
  })
  status: PodcastStatus;

  @Prop()
  filePath?: string;

  @Prop({ required: true, default: () => new Date() })
  createdAt: Date;

  @Prop({ required: true, default: () => new Date() })
  updatedAt: Date;
}

export const PodcastSchema = SchemaFactory.createForClass(Podcast);
