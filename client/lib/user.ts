export interface User {
    id: string;
    full_name: string;
    name: string;
    discriminator: number;
    url: string;
    avatar?: string;
    pronouns?: string;
    flair: string;
    twitch_name?: string;
    twitch_display_name?: string;
    twitch_channel?: string;
    can_moderate: boolean;
}