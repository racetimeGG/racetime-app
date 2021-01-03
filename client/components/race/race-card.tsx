import React from "react";
import Link from "next/link";
import {Race} from "../../lib/race";

import styles from "../../styles/components/race/race-card.module.scss";
import Statistic from "../ui/statistic";
import {durationToTimer} from "../../lib/utils";

interface RaceCardProps {
    race: Race;
}

export default function RaceCard(props: RaceCardProps) {
    const duration = durationToTimer(new Date(props.race.started_at), new Date(props.race.ended_at));

    return (
        <div className={styles.shell}>
            <span className={styles.slug}>{props.race.name}</span>
            <Link href={"/race" + props.race.url}>
                <a>
                    <div className={styles.raceCard}>
                        <div className={styles.goal}>{props.race.goal.name}</div>
                        <div className={styles.body}>
                            <div className={styles.info}>
                                {props.race.info}
                            </div>
                            <Statistic value={props.race.entrants_count} label="Entrants"/>
                            <Statistic value={props.race.entrants_count_finished} label="Finishers"/>
                            <Statistic value={duration} label="Finish time"/>
                        </div>
                    </div>
                </a>
            </Link>
        </div>
    );
}