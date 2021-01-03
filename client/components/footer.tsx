import React from "react";
import Link from "next/link";
import {FontAwesomeIcon} from "@fortawesome/react-fontawesome";

import styles from "./../styles/components/footer.module.scss";
import {faBuilding, faCode, faComments, faGavel, faQuestionCircle} from "@fortawesome/free-solid-svg-icons";
import {faDiscord, faGithub, faPatreon, faTwitter} from "@fortawesome/free-brands-svg-icons";


export default function Footer() {
    return (
        <div className={styles.footer}>
            <div className={styles.links}>
                <ul>
                    <li className={styles.link}>
                        <Link href="/help">
                            <a><FontAwesomeIcon icon={faQuestionCircle}/><span>Help &amp; support</span></a>
                        </Link>
                    </li>
                    <li className={styles.link}>
                        <FontAwesomeIcon icon={faComments}/><span>FAQ</span>
                    </li>
                    <li className={styles.link}>
                        <FontAwesomeIcon icon={faBuilding}/><span>About</span>
                    </li>
                    <li className={styles.link}>
                        <FontAwesomeIcon icon={faGavel}/><span>Rules</span>
                    </li>
                    <li className={styles.link}>
                        <FontAwesomeIcon icon={faCode}/><span>API &amp; docs</span>
                    </li>
                </ul>

                <ul>
                    <li className={styles.link}>
                        <a href="https://discord.racetime.gg">
                            <FontAwesomeIcon icon={faDiscord}/>
                            <span>Discord</span>
                        </a>
                    </li>
                    <li className={styles.link}>
                        <a href="https://github.com/racetimeGG">
                            <FontAwesomeIcon icon={faGithub}/>
                            <span>GitHub</span>
                        </a>
                    </li>
                    <li className={styles.link}>
                        <a href="https://twitter.com/racetimeGG">
                            <FontAwesomeIcon icon={faTwitter}/>
                            <span>Twitter</span>
                        </a>
                    </li>
                    <li className={styles.patreonLink}>
                        <a href="https://www.patreon.com/racetimeGG">
                            <FontAwesomeIcon icon={faPatreon}/>
                            <span>Patreon</span>
                        </a>
                    </li>
                </ul>
            </div>
            <div className={styles.spacer}/>
            <div className={styles.motd}>
                <span>Good luck and be fast</span>
            </div>
        </div>
    )
}