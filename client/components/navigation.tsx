import {faSignOutAlt, faUserEdit} from "@fortawesome/free-solid-svg-icons";
import {FontAwesomeIcon} from "@fortawesome/react-fontawesome";
import Link from "next/link";
import React from "react";

import styles from "./../styles/components/navigation.module.scss";

export default function Navigation() {
    return (
        <div className={styles.nav}>
            <Link href="/"><a>
                <div className={styles.logo}>
                    <img className={styles.icon} alt="racetime.gg logo" src="/icon.svg"/>
                    <span className={styles.name}>racetime.gg</span>
                </div>
            </a></Link>
            <div className={styles.item}><Link href="/categories">Categories</Link></div>
            <div className={styles.item}>Races</div>
            <span className={styles.spacer}/>
            <div className={styles.profile}>
                <span className={styles.up}>Hello, Spell</span>
                <Link href="/user/edit"><a><FontAwesomeIcon icon={faUserEdit} className={styles.upIcon}/></a></Link>
                <Link href="/user/logout"><a><FontAwesomeIcon icon={faSignOutAlt} className={styles.upIcon}/></a></Link>
            </div>
        </div>
    );
}