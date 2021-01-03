export interface Race {
    name: string;
    status: {
        value: string;
        verbose_value: string;
        help_text: string;
    };
    url: string;
    data_url: string;
    goal: {
        name: string;
        custom: boolean;
    }
    info: string;
    entrants_count: number;
    entrants_count_finished: number;
    entrants_count_inactive: number;
    opened_at: Date;
    started_at: Date;
    time_limit: string;
    ended_at: Date;
    recordable: boolean;
    recorded: boolean;
}

export interface RacesData {
    count: number;
    num_pages: number;
    races: Race[];
}
