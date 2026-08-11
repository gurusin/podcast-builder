import { IsIn, IsString, MinLength } from 'class-validator';

export class CreatePodcastDto {
  @IsString()
  @MinLength(1)
  topic: string;

  @IsIn(['short', 'medium', 'long'])
  durationHint: 'short' | 'medium' | 'long';
}
