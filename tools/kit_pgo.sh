# tools/kit_pgo.sh: record both speed-tuning profiles through the player's build path (tools/rr_compile.py),
# so profile names match players' builds wherever they install. Results: C:/mgpgo/k_prof, C:/mgpgo/kv_prof.
cd /c/RumbleRecomp
D=C:/mgpgo/kittest
WSC=wk_forest4_group.sav,wk_lobby4.sav,wk_royale_r1.sav,wk_forest_group.sav,wk_forest4_start.sav,wk_royale_r2.sav,wk_hub4.sav,wk_forest_start.sav,br_rankb_f.sav,wk_hub.sav,wk_royale_r1.sav,wk_forest4_group.sav,wk_royale_r2.sav
for v in weekend:k_prof vanilla:kv_prof; do
  name=${v%%:*}; P=C:/mgpgo/${v##*:}
  python tools/rr_compile.py $name --data $D --instrument || exit 1
  [ $name = weekend ] && M=$D/build/weekend_instrumented/gWPSE01_weekend_recomp.dll || M=$D/build/vanilla_instrumented/gWPSE01_recomp.dll
  rm -rf $P
  if [ $name = weekend ]; then
    RUMBLE_RANDOMIZER=559 python tools/rr_pgo_train.py --launch --module $M --profile-dir $P --wad patches/out/weekend15_patch1.wad --scenes $WSC || exit 2
  else
    python tools/rr_pgo_train.py --launch --module $M --profile-dir $P || exit 2
  fi
  llvm-profdata merge -o $P/merged.profdata $P/raw/*.profraw || exit 3
  cp $P/merged.profdata kit/pgo/$name.profdata
  python tools/rr_compile.py $name --data $D || exit 4
done
echo ALL_DONE
