import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { PodcastStatus } from '../../common/enums/podcast-status.enum';
import { Podcast, PodcastDocument } from '../schemas/podcast.schema';
import {
  CreatePodcastData,
  IPodcastRepository,
} from './podcast.repository.interface';

@Injectable()
export class PodcastRepository implements IPodcastRepository {
  constructor(
    @InjectModel(Podcast.name)
    private readonly podcastModel: Model<PodcastDocument>,
  ) {}

  async create(data: CreatePodcastData): Promise<PodcastDocument> {
    const created = new this.podcastModel(data);
    return created.save();
  }

  async findById(podcastId: string): Promise<PodcastDocument | null> {
    return this.podcastModel.findOne({ podcastId }).exec();
  }

  async updateStatus(
    podcastId: string,
    status: PodcastStatus,
    filePath?: string,
  ): Promise<PodcastDocument | null> {
    const update: Partial<Podcast> & { updatedAt: Date } = {
      status,
      updatedAt: new Date(),
    };

    if (filePath !== undefined) {
      update.filePath = filePath;
    }

    return this.podcastModel
      .findOneAndUpdate({ podcastId }, { $set: update }, { new: true })
      .exec();
  }
}
