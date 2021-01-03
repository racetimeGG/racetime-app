import React from "react";
import Link from "next/link";

import {User} from "../../lib/user";
import styles from "../../styles/components/user/inline-user-profile.module.scss";

export interface InlineUserProfileProps {
    user: User;
}

export default function InlineUserProfile(props: InlineUserProfileProps) {
    return (
        <Link href={props.user.url}>
            <a className={styles.inline}>
                {props.user.avatar && <img className={styles.avatar} src={props.user.avatar} alt={props.user.name}/>}
                <span>{props.user.full_name}</span>
           </a>
        </Link>
    );
}