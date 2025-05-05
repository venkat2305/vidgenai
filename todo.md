<!-- 1. api versioning -->
<!-- 2. r2 instead of s3 -->
3. use whisper-timestamped instead of openai-whisper
4. datetime.utcnow is deprected, modify it, also keep some project instruction for next projects. 
5. since we have to create a factual script, we might need to use gemini flash with search grounding. 
6. fetch images based on the script generated and then use accordingly. 
7. instead of serp, use google's search to get the images. 
8. lets do 720p videos and compress them. i think we have to use ffmpeg and not moviepy
9. upload audio, images, videos in background asynchrounously. 
10. understand r2 upload and its config properly. 
11. structure the folders properly in cloudflare.
12. use groq whisper to get the transcriptions. 
<!-- 13. fix thumbnail image upload issues.  -->
14. get images based on the transcript section, so we put relevant images for that part of the video.
15. production r2 url so we can enable caching.
16. scroll means go to next reel, mobile responsive
17. play pause button.
<!-- 18. when we click on unmute button on a reel in explore page we are essentially opening a new page right, lets dont do that instead simply unmute and play the audio.  -->
19. we are using groq, gemini clients many where on the code base, do we create once and use it everywhere, would it improve any perf?
20. store times taken for different stages. 