<!-- 1. api versioning -->
<!-- 2. r2 instead of s3 -->
<!-- 3. use whisper-timestamped instead of openai-whisper -->
<!-- 4. datetime.utcnow is deprected, modify it, also keep some project instruction for next projects.  -->
<!-- 5. since we have to create a factual script, we might need to use gemini flash with search grounding. -->

6. fetch images based on the script generated and then use accordingly.
7. instead of serp, use google's search to get the images.
8. lets do 720p videos and compress them. i think we have to use ffmpeg and not moviepy
9. upload audio, images, videos in background asynchrounously.
10. understand r2 upload and its config properly.
11. structure the folders properly in cloudflare.
    <!-- 12. use groq whisper to get the transcriptions.  -->
    <!-- 13. fix thumbnail image upload issues.  -->
12. get images based on the transcript section, so we put relevant images for that part of the video.
13. production r2 url so we can enable caching.
14. scroll means go to next reel, mobile responsive
15. play pause button.
    <!-- 18. when we click on unmute button on a reel in explore page we are essentially opening a new page right, lets dont do that instead simply unmute and play the audio.  -->
    <!-- 19. we are using groq, gemini clients many where on the code base, do we create once and use it everywhere, would it improve any perf? -->
16. store times taken for different stages.
17. optimze the backend. [link](https://t3.chat/chat/3fe35d86-e144-4081-b9da-9cec19e7c076)
18. no need for api/routes. lets just have routes folder.
19. using async clients, requests wherever possible for network requests. research if we can use async in other areas of the application.
20. put models names in a proper way, remove them from env.
21. video composing part we can do it in colab or laptop, we can put that in pending and do all that composing and upload it to r2 and update db from there. this would enables us to build higher quality videos.
22. we can also add some background audio's or sound effects with eleven labs api.
23. eleven labs dubbing api to make videos in multiple languages.
24. multiple language support.
25.
26. eleven labs also returns characters for second or something like that, I have to use it. but other voice providers may not return that so we have to handle this carefully.
27. subtitle style, with coloring to the word being spoke dynamic styles and nice font.
28. we have to do different process parallely, since it is just network calls, that would be better if we can do them parallely.
29. lets try to fetch, use images without watermark.
30.
31. for ai generated images, we have to generate a lot of details so that images in all scenes will have same style etc to make the viewers believe we made an engaging story.
32. we can use other services, but lets stick to gemini wherever possible, because if in case we get more users, everything will fail, if used, we need to have a lot of fall backs
33. we have to generate a lot of videos, we need to have a colab in which it processes the videos one by one, we can then send a notification to the user about it.
34. Dont use llama 3.3 70b anywhere, use llama 4 maverick.
35. login with differnt social platform like youtube so as to allow the users to post the content from anywhere.
36.
37. implement rate limiting
38. implement best security practices. [chatgpt](https://chatgpt.com/c/68093130-6d70-800a-8658-ba6c5a5e063d)
39. write tests
40. we have to show script first, let the user's edit script. if all ok, then we can proceed with video generation. we can even fetch images and let user decide which to keep and which to remove.
41. sign in with mock account, which has a youtube channel logged in so users can test them.

Manim

- new 2.5 pro for manim code gen and run that to get the videos.
- for manim, to run llm generated code, use something like manim.
- with manim video gen, we have to give options whether to produce audio or not. we have to run this manim llm code in a sandbox environment.
- for manim code generation, we have to give proper working examples.

You’ve dealt with queues, sockets, streaming, or real-time infra. Or want to.
You’ve worked on systems where latency, uptime, and scale actually matter

pinterest image api? apify
what is the best way to aggregate or get images. 

SCENE
- json2video
- we can generate scenes, script for that scene, image prompt for this scene
- so if we have an video editor online, we can give them option to change image or script for a particular scene without affecting eveything.  

Images and Videos:
- compress images, videos to appropriate quality.
- if watermark is present dont use it.
- do contextual images properly.
- 
