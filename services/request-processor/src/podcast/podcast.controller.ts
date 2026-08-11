import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  Post,
} from '@nestjs/common';
import * as path from 'path';
import { CommandBus, QueryBus } from '@nestjs/cqrs';
import { CreatePodcastDto } from './dto/create-podcast.dto';
import { CreatePodcastCommand } from './commands/create-podcast.command';
import { CreatePodcastResult } from './commands/handlers/create-podcast.handler';
import { GetPodcastStatusQuery } from './queries/get-podcast-status.query';
import { PodcastDocument } from './schemas/podcast.schema';
import { PodcastStatus } from '../common/enums/podcast-status.enum';

interface CreatePodcastResponse {
  podcastId: string;
  status: PodcastStatus;
}

interface PodcastStatusResponse {
  podcastId: string;
  topic: string;
  durationHint: string;
  status: PodcastStatus;
  audioUrl: string | null;
  createdAt: Date;
  updatedAt: Date;
}

@Controller('podcasts')
export class PodcastController {
  constructor(
    private readonly commandBus: CommandBus,
    private readonly queryBus: QueryBus,
  ) {}

  @Post()
  @HttpCode(HttpStatus.ACCEPTED)
  async createPodcast(
    @Body() dto: CreatePodcastDto,
  ): Promise<CreatePodcastResponse> {
    const result = await this.commandBus.execute<
      CreatePodcastCommand,
      CreatePodcastResult
    >(new CreatePodcastCommand(dto.topic, dto.durationHint));

    return { podcastId: result.podcastId, status: PodcastStatus.PENDING };
  }

  @Get(':id')
  async getPodcastStatus(@Param('id') id: string): Promise<PodcastStatusResponse> {
    const podcast = await this.queryBus.execute<GetPodcastStatusQuery, PodcastDocument>(
      new GetPodcastStatusQuery(id),
    );

    // Derive a browser/curl-ready audio URL from the stored file path.
    // filePath is the container-internal path e.g. /app/podcasts/<uuid>.mp3
    // Nginx serves ./podcasts/ at /audio/, so we expose just the filename.
    const audioUrl =
      podcast.filePath && podcast.status === PodcastStatus.DONE
        ? `/audio/${path.basename(podcast.filePath)}`
        : null;

    return {
      podcastId: podcast.podcastId,
      topic: podcast.topic,
      durationHint: podcast.durationHint,
      status: podcast.status,
      audioUrl,
      createdAt: podcast.createdAt,
      updatedAt: podcast.updatedAt,
    };
  }
}
