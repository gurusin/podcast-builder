import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  Post,
} from '@nestjs/common';
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
  async getPodcastStatus(@Param('id') id: string): Promise<PodcastDocument> {
    return this.queryBus.execute<GetPodcastStatusQuery, PodcastDocument>(
      new GetPodcastStatusQuery(id),
    );
  }
}
