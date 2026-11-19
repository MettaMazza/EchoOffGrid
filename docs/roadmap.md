# Networking roadmap

EchoOffGrid is in active development. The current preview runs a local workstation on each device. Users can pair one Mac and one Android phone over a trusted USB connection. A background worker exchanges compatible files over authenticated USB forwarding or local Wi-Fi. Optional receiver logs record observations from radio hardware.

## Next stage · Peer-to-peer and mesh networking

| Proposed milestone | What a successful test would show |
| --- | --- |
| Trusted peer exchange | Two independently installed peers can approve each other, choose a collection and exchange it without a central catalogue or the original Mac. |
| Interrupted transfers | A transfer survives disconnection and rejoining. The receiver verifies the completed file and both devices show its status. |
| Low-bandwidth mesh trial | A short message or inventory update travels between test nodes. The interface shows its source, age and delivery state. Larger media can wait for a higher-bandwidth connection. |
| Multi-hop evaluation | A third consenting test node forwards an item across two hops. Duplicate suppression, expiry, withdrawal of trust and storage limits are exercised. |

Transport choices and compatible hardware will follow prototype measurements. Radio support stays optional. These milestones describe planned engineering work and carry no release date.
