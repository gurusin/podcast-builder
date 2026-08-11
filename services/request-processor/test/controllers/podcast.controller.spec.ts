import { Test, TestingModule } from '@nestjs/testing';
import { HttpStatus, NotFoundException } from '@nestjs/common';
import { CommandBus, CqrsModule, QueryBus } from '@nestjs/cqrs';
import * as request from 'supertest';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { PodcastController } from '../../src/podcast/podcast.controller';
import { PodcastStatus } from '../../src/common/enums/podcast-status.enum';
import { PodcastDocument } from '../../src/podcast/schemas/podcast.schema';

describe('PodcastController (e2e)', () => {
  let app: INestApplication;
  let commandBus: jest.Mocked<CommandBus>;
  let queryBus: jest.Mocked<QueryBus>;

  const mockPodcast = {
    podcastId: 'ctrl-uuid-123',
    topic: 'Renewable Energy',
    durationHint: 'short',
    status: PodcastStatus.PENDING,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  } as unknown as PodcastDocument;

  beforeEach(async () => {
    const commandBusMock: Partial<jest.Mocked<CommandBus>> = {
      execute: jest.fn(),
    };
    const queryBusMock: Partial<jest.Mocked<QueryBus>> = {
      execute: jest.fn(),
    };

    const moduleRef: TestingModule = await Test.createTestingModule({
      imports: [CqrsModule],
      controllers: [PodcastController],
    })
      .overrideProvider(CommandBus)
      .useValue(commandBusMock)
      .overrideProvider(QueryBus)
      .useValue(queryBusMock)
      .compile();

    app = moduleRef.createNestApplication();
    app.useGlobalPipes(
      new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true }),
    );
    await app.init();

    commandBus = moduleRef.get(CommandBus) as jest.Mocked<CommandBus>;
    queryBus = moduleRef.get(QueryBus) as jest.Mocked<QueryBus>;
  });

  afterEach(async () => {
    await app.close();
  });

  describe('POST /podcasts', () => {
    it('should return 202 with podcastId and status PENDING', async () => {
      (commandBus.execute as jest.Mock).mockResolvedValue({
        podcastId: 'ctrl-uuid-123',
      });

      const response = await request(app.getHttpServer())
        .post('/podcasts')
        .send({ topic: 'Renewable Energy', durationHint: 'short' })
        .expect(HttpStatus.ACCEPTED);

      expect(response.body).toEqual({
        podcastId: 'ctrl-uuid-123',
        status: PodcastStatus.PENDING,
      });
      expect(commandBus.execute).toHaveBeenCalledTimes(1);
    });

    it('should return 400 when topic is missing', async () => {
      await request(app.getHttpServer())
        .post('/podcasts')
        .send({ durationHint: 'short' })
        .expect(HttpStatus.BAD_REQUEST);
    });

    it('should return 400 when durationHint is invalid', async () => {
      await request(app.getHttpServer())
        .post('/podcasts')
        .send({ topic: 'Test topic', durationHint: 'extra-long' })
        .expect(HttpStatus.BAD_REQUEST);
    });
  });

  describe('GET /podcasts/:id', () => {
    it('should return the podcast document when found', async () => {
      (queryBus.execute as jest.Mock).mockResolvedValue(mockPodcast);

      const response = await request(app.getHttpServer())
        .get('/podcasts/ctrl-uuid-123')
        .expect(HttpStatus.OK);

      expect(response.body.podcastId).toBe('ctrl-uuid-123');
      expect(response.body.status).toBe(PodcastStatus.PENDING);
      expect(queryBus.execute).toHaveBeenCalledTimes(1);
    });

    it('should return 404 when the podcast is not found', async () => {
      (queryBus.execute as jest.Mock).mockRejectedValue(
        new NotFoundException('Podcast with id "nonexistent" not found'),
      );

      await request(app.getHttpServer())
        .get('/podcasts/nonexistent')
        .expect(HttpStatus.NOT_FOUND);
    });
  });
});
