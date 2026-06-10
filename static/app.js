import { TalkingHead } from "talkinghead";

const head = new TalkingHead(document.getElementById("avatar"), {
  lipsyncModules: ["en"],
});
let head = null;
let = animationMixer = null; 
let currentAnimation = null; 

try {
  await head.showAvatar({
    url: "/TalkingHead/avatars/brunette.glb",
    body: "F",
    avatarMood: "neutral",
    lipsyncLang: "en",
  });
} catch (error) {
  console.error("Avatar konnte nicht geladen werden:", error);
}