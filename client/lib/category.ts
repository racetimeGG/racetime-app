import {User} from "./user";
import {Race} from "./race";

export interface Category {
    url: string;
    name: string;
    short_name: string;
    slug: string;
    image?: string;
    streaming_required: boolean;
}

export interface CategoryDetail extends Category {
    owners: User[];
    moderators: User[];
}

export interface CategoryStats extends Category {
    archived: boolean;
    race_count: number;
    current_race_count: number;
    open_race_count: number;
    finished_race_count: number;
}

export function isCategoryStats(category: Category): category is CategoryStats {
    return (category as CategoryStats).race_count !== undefined;
}
