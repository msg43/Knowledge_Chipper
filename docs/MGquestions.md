Specifically there are a bunch of files in V2 which are meant to generate a far more advanced summarizer which will ultimately replace the existing summarizer function.  So I am trying to ask you to analyze the difference between a) the newly added files in V2 which don't exist in the main branch and b) the existing summarization function in the main branch.  For instance, the main branch summarizer uses 95% of the token window.  The new files in V2 are meant to use much much smaller parts of the context window to maximize attention and detail extraction.  


Ignore the plan.md and todo.md files and focus on the actual files that were created by those documents.  The original (same as main) summarizer module in V2 hasn't been swapped out yet for the new functionality, but the new files should have been created in keeping with the plan.md and todo.md


How about you Create a new .MD file where you write a detailed analysis of what summarization functions exist in the V2 branch. Then switch to the main branch and write a similar detailed analysis. Then come back to me with a response which uses those 2.MD files as a basis for a accurate and detailed comparison.
