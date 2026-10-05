import { useEffect, useState } from 'react'
import { Image, type ImageProps } from 'expo-image'
import {
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native'
import { colors } from '../constants/theme'
import type { FoodImageAsset } from '../data/foodAssetManifest'

interface FoodImageProps extends Omit<ImageProps, 'resizeMode' | 'source'> {
  name: string
  source: FoodImageAsset | null
}

export function FoodImage({ name, onError, source, style, ...props }: FoodImageProps) {
  const [failed, setFailed] = useState(false)
  const uri = source?.uri ?? null

  useEffect(() => {
    setFailed(false)
  }, [uri])

  if (!uri || failed) {
    return (
      <View
        accessibilityLabel={name}
        style={[styles.fallback, style as StyleProp<ViewStyle>]}
      >
        <Text adjustsFontSizeToFit numberOfLines={2} style={styles.fallbackText}>
          {name}
        </Text>
      </View>
    )
  }

  return (
    <Image
      {...props}
      accessibilityLabel={props.accessibilityLabel ?? name}
      cachePolicy="memory-disk"
      onError={(event) => {
        setFailed(true)
        onError?.(event)
      }}
      source={{ uri }}
      style={style}
    />
  )
}

const styles = StyleSheet.create({
  fallback: {
    alignItems: 'center',
    backgroundColor: colors.cream,
    justifyContent: 'center',
    overflow: 'hidden',
    paddingHorizontal: 6,
  },
  fallbackText: {
    color: colors.muted,
    fontSize: 10,
    fontWeight: '800',
    lineHeight: 13,
    textAlign: 'center',
  },
})
