import React from "react";
import {CategoryDetail} from "../../lib/category";

import styles from "../../styles/components/category/category-header.module.scss";
import InlineUserProfile from "../user/inline-user-profile";


interface CategoryHeaderProps {
    category: CategoryDetail;
}

export default function CategoryHeader(props: CategoryHeaderProps) {
    return (
        <div className={styles.header}>
            <div className={styles.headerLeft}>
                <h1 className={styles.name}>
                    {props.category.name} <span className={styles.shortName}>{props.category.short_name}</span>
                </h1>
            </div>
            <div className={styles.headerRight}>
                <h2>Owners</h2>
                <div>
                    {props.category.owners.map(owner => (
                        <React.Fragment key={owner.id}><InlineUserProfile user={owner}/> </React.Fragment>
                    ))}
                </div>
                <h2>Moderators</h2>
                <div>
                    {props.category.moderators.map(mod => (
                        <React.Fragment key={mod.id}><InlineUserProfile user={mod}/> </React.Fragment>
                    ))}
                </div>
            </div>
        </div>
    );
}
