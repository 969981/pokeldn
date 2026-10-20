-- Lua 5.4 helper for a single experimental subject=5 reward row.
-- Compile with: luac -o sv400_charm_single_append_helper.luac sv400_charm_single_append_helper.lua
-- Repacking the helper alone is NOT a verified Pokemon Violet Mod.
-- Haxe anonymous-struct compatibility, game load, bag and save are NOT verified.
return function(reward)
  if reward == nil then return end
  local rows = reward[3]
  if rows == nil or rows.length == nil or rows.length >= 45 then return end
  local names = { ItemNo=true, ItemNum=true, rareType=true, subjectType=true }
  local item = { ItemNo=492, ItemNum=1, rareType=0, subjectType=5, __fields__=names }
  rows:push(item)
end
