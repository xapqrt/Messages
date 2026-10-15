package com.anindra.messages.display

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.anindra.messages.R

@Composable
fun ResultDisplayNotice() {
    Text(
        stringResource(R.string.result_display_custom),
        style = MaterialTheme.typography.labelSmall,
        modifier = Modifier.padding(start = 14.dp, end = 14.dp, bottom = 8.dp)
    )
}
